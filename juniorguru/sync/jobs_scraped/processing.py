import gzip
import importlib
import json
import os
from datetime import date
from multiprocessing import JoinableQueue as Queue, Process
from pathlib import Path
from pprint import pformat
from queue import Empty

from peewee import IntegrityError

from juniorguru.lib import loggers
from juniorguru.models.base import db
from juniorguru.models.job import ScrapedJob


WORKERS = os.cpu_count()

LOGGING_PARSER_BATCH_SIZE = 100

LOGGING_WRITER_BATCH_SIZE = 1000

LOGGING_POSTPROCESSOR_BATCH_SIZE = 100

LOGGING_PERSISTOR_BATCH_SIZE = 100


logger = loggers.from_path(__file__)


# HELLO, ADVENTURER! You're very welcome to study this monstrosity.
# However, I advise you to go through the following notes first:
#
# - This processing is a part of a larger scheme of things, which aren't very well
#   documented. The basics are: juniorguru.jobs contains a Scrapy project with
#   scrapers for downloading job postings. Scraped data is stored raw as .jsonl.gz
#   files and those are persisted between junior.guru builds. Then this part,
#   processing, happens. It reads the data, preprocesses them with pipelines, merges
#   duplicities, postprocesses the db records with pipelines. Then the rest
#   of the app can finally consider the jobs to be ready to work with.
# - The downloading and processing parts are intentionally separate. Having them
#   together didn't prove to be a good strategy. It makes debugging difficult,
#   it makes difficult to persist data between builds, it makes harder to postprocess
#   the same data differently over time, and so on. Also postprocessing directly
#   in Scrapy pipelines doesn't really scale well. Scrapy is good for downloading
#   items per scraper, not for source-agnostic concurrent CPU-heavy postprocessing.
# - Some ideas are borrowed from the Scrapy framework, but mind this is not
#   Scrapy, this is custom code based on custom ideas. Yes, there are pipelines,
#   there is a DropItem exception, there's even something called item, but they're
#   not Scrapy-compatible and they're not the same. The items here are plain dicts.
#   The pipelines are plain functions, not classes.
# - The code uses multiprocessing Queues and Processes, because, and I really
#   really tried, Pools don't work well with the use cases here. Pools abstract
#   away some stuff, while Queues allow for elegant solutions to consumer/producer
#   scenarios as well as full control over how the db connection is managed.
#   Using Pools caused various problems from memory issues to db connection
#   mismanagement.
# - The work done here is memory-heavy, so some of the code is ugly for the sake
#   of optimizations made. Especially Peewee Job objects can be difficult to pass
#   around multiple processes.
# - SQLite doesn't handle concurrent writing well. Concurrent reading is okay.
#   So the bottleneck here is to save the items to the db, or to save changes made.


class DropItem(Exception):
    pass


def filter_relevant_paths(paths, last_seen_on):
    """
    Filters given .json.gz paths so that only those scraped
    on equal or later date than 'last_seen_on' are left.
    """
    paths = [Path(path) for path in paths]
    dirs = {path.parent for path in paths}
    dirs = [dir for dir in dirs if dir_to_date(dir) >= last_seen_on]
    return [path for path in paths if path.parent in dirs]


def sort_by_size(paths):
    return sorted(paths, key=lambda path: path.stat().st_size, reverse=True)


def process_paths(paths, pipelines, workers=None):
    """
    Load given paths (files) to the database. Before loading, process
    each item through given pipelines. Merge duplicate items on save.
    """
    workers = workers or WORKERS

    # First we create the path queue and fill it with paths pointing
    # at .jsonl.gz files we want to parse.
    path_queue = Queue()
    for path in sort_by_size(paths):
        path_queue.put(str(path))

    # Then we create the item queue, which will collect parsed items.
    # The writer process starts, waiting for the item queue. The process
    # being deamon means that it's going to be terminated automatically
    # once this program is done and doesn't need to be managed manually.
    item_queue = Queue()
    Process(target=_writer, args=(item_queue,), daemon=True).start()

    # Reader processes get started, pop paths from the path queue, stream
    # the .jsonl.gz files, parse each line, and put individual items to
    # the item queue. From there the writer process takes care of saving
    # them to the db and merging the same jobs. This intentionally happens
    # in a single process so that SQLite isn't overloaded by concurrent writes.
    readers = []
    for reader_id in range(workers):
        proc = Process(target=_reader, args=(reader_id, path_queue, item_queue, pipelines))
        readers.append(proc)
        proc.start()

    for joinable in readers + [path_queue, item_queue]:
        joinable.join()


def _reader(id, path_queue, item_queue, pipelines):
    """
    Processes taking care of reading .jsonl.gz files, parsing them to items,
    preprocessing the items with given pipelines, and putting the items
    to a queue to be saved to the db.
    """
    logger_r = logger[f'readers.{id}']
    logger_r.debug(f"Starting, preprocessing pipelines: {pipelines!r}")
    pipelines = load_pipelines(pipelines)
    try:
        while True:
            path = path_queue.get(timeout=1)
            logger_r.debug(f"Parsing {path}")
            counter = 0
            try:
                for item in parse(path):
                    try:
                        item = execute_pipelines(item, pipelines)
                    except DropItem as e:
                        logger_r.warning(f"Dropping {item!r}, reason: {e}")
                    else:
                        item_queue.put(item)
                        counter += 1
                        if counter % LOGGING_PARSER_BATCH_SIZE == 0:
                            logger_r.info(f"Parsing {path}, {counter} items")
            finally:
                logger_r.info(f"Done parsing {path}, {counter} items total")
                path_queue.task_done()
    except Empty:
        logger_r.debug("Nothing else to parse, closing")


def parse(path):
    """
    Parse given .jsonl.gz file, generate items, i.e. dicts with scraped
    job data.
    """
    try:
        with gzip.open(path, 'rt') as f:
            for line_no, line in enumerate(f, start=1):
                yield parse_line(path, line_no, line)
    except EOFError:
        logger['parse'].error(f'Unreadable file, probably empty: {path}')
        return
    except Exception:
        logger['parse'].exception(f'Error parsing file: {path}')
        raise


def parse_line(path, line_no, line):
    """
    Parse a single line of a .jsonl.gz file. Return an item, i.e. dict with
    scraped job data.
    """
    try:
        data = json.loads(line)
        data['first_seen_on'] = date.fromisoformat(data['first_seen_on'])
        data['last_seen_on'] = path_to_date(path)
        return data
    except Exception:
        logger['parse'].error(f'Error parsing the following data:\n\n{line}\n\n'
                              f'Line number: {line_no}, file: {path}')
        raise


@db.connection_context()
def _writer(item_queue):
    """
    A single process taking care of writing items to the db
    and merging them in case of duplicities.
    """
    logger_w = logger['writer']
    logger_w.debug("Starting")
    counter = 0
    try:
        while True:
            item = item_queue.get()
            logger_w.debug(f"Saving {item['url']}")
            job = ScrapedJob.from_item(item)
            try:
                job.save()
            except IntegrityError:
                job = ScrapedJob.get_by_item(item)
                job.merge_item(item)
                job.save()
            except Exception:
                logger_w.error(f'Error saving the following item:\n{pformat(item)}')
                raise
            else:
                logger_w.debug(f"Saved {item['url']} as {job!r}")
            finally:
                counter += 1
                if counter % LOGGING_WRITER_BATCH_SIZE == 0:
                    logger_w.info(f"Saved {counter} items so far")
                item_queue.task_done()
    finally:
        logger_w.info(f"Saved {counter} items total")
        logger_w.debug("Closing")


def postprocess_jobs(pipelines, workers=None):
    """
    Take jobs from the database and apply given postprocessing pipeline
    on the data. Then update the jobs with the changes.
    """
    workers = workers or WORKERS

    # First we create the ID queue and start a separate process, which
    # queries the db and fills the queue with IDs of all the jobs.
    # The process being deamon means that it's going to be terminated
    # automatically once this program is done and doesn't need to be
    # managed manually.
    id_queue = Queue()
    Process(target=_query, args=(id_queue,), daemon=True).start()

    # Then we create the queue for operations. Operation is a tuple
    # containing a string like 'save' or 'delete', and then a dict with
    # the job data. We start a separate process responsible for executing
    # the operations. This intentionally happens in a single process so
    # that SQLite isn't overloaded by concurrent writes.
    op_queue = Queue()
    Process(target=_persistor, args=(op_queue,), daemon=True).start()

    # Postprocessor processes get started. They pop IDs of jobs from the
    # ID queue, fetch the jobs by ID from the db (concurrent reads are OK),
    # then turn the job into a dict, and run the pipelines over the dict.
    # If the pipelines raise DropItem, a 'delete' operation is returned with
    # a minimalistic dict containing only the ID of the job to delete. Else
    # a 'save' operation with a dict of data to update is returned to the
    # operation queue.
    postprocessors = []
    for postprocessor_id in range(workers):
        proc = Process(target=_postprocessor, args=(postprocessor_id, op_queue, id_queue, pipelines))
        postprocessors.append(proc)
        proc.start()

    for joinable in postprocessors + [op_queue, id_queue]:
        joinable.join()


db.connection_context()
def _query(id_queue):
    """
    A single process taking care of listing all jobs in the db
    and putting their IDs to the ID queue for postprocessing.
    """
    for job in ScrapedJob.select(ScrapedJob.id).iterator():
        id_queue.put(job.id)


db.connection_context()
def _postprocessor(id, op_queue, id_queue, pipelines):
    """
    Processes taking care of passing items through the postprocessing
    pipelines.
    """
    logger_p = logger[f'postprocessors.{id}']
    logger_p.debug(f"Starting, preprocessing pipelines: {pipelines!r}")
    pipelines = load_pipelines(pipelines)
    counter = 0
    try:
        while True:
            job_id = id_queue.get(timeout=1)
            job = ScrapedJob.get(job_id)
            logger_p.debug(f"Executing pipelines for {job!r}")
            item = job.to_item()
            try:
                op_queue.put(('save', execute_pipelines(item, pipelines)))
            except DropItem:
                logger_p.info(f"Dropping {job!r}")
                op_queue.put(('delete', {'id': job_id}))
            except Exception as e:
                logger_p.exception(f"Executing pipelines for {job!r} failed: {e}")
                op_queue.put(('delete', {'id': job_id}))
            finally:
                counter += 1
                if counter % LOGGING_POSTPROCESSOR_BATCH_SIZE == 0:
                    logger_p.info(f"Processed pipelines for {counter} jobs so far")
                id_queue.task_done()
    except Empty:
        logger_p.info(f"Processed pipelines for {counter} jobs total")
        logger_p.debug("Nothing else to postprocess, closing")


@db.connection_context()
def _persistor(op_queue):
    """
    A single process taking care of persisting the changes made
    by postprocessing pipelines.
    """
    logger_p = logger['persistor']
    logger_p.debug("Starting")
    counter = 0
    try:
        while True:
            operation, item = op_queue.get()
            job = ScrapedJob.from_item(item)
            try:
                if operation == 'delete':
                    logger_p.debug(f"Deleting {job!r}")
                    job.delete_instance()
                elif operation == 'save':
                    logger_p.debug(f"Updating {job!r}")
                    job.save()
                else:
                    raise ValueError(f'Unknown operation: {operation}')
            except Exception:
                logger_p.error(f'Error saving the following item:\n{pformat(item)}')
                raise
            finally:
                del job
                counter += 1
                if counter % LOGGING_PERSISTOR_BATCH_SIZE == 0:
                    logger_p.info(f"Updated {counter} jobs so far")
                op_queue.task_done()
    finally:
        logger_p.info(f"Updated {counter} jobs total")
        logger_p.debug("Closing")


def load_pipelines(pipelines):
    """
    Take a list of strings, import paths to pipeline modules,
    import them, and return the 'process' function from each
    of them.
    """
    return [importlib.import_module(pipeline).process
            for pipeline in pipelines]


def execute_pipelines(item, pipelines):
    """
    Takes an 'item' dict and a list of 'process' functions
    (see 'load_pipelines'). Returns the 'item' dict as it is
    returned after processing through the functions.

    The 'process' function is expected to take the dict and
    return the same dict modified, or return a different
    one with the same data, modified. It can also raise
    the DropItem exception to signalize that the 'item'
    it is processing should instead be deleted for some reason.
    """
    for pipeline in pipelines:
        item = pipeline(item)
    return item


def path_to_date(path):
    """
    Parse date when the scrapping has happened from given path
    to a .jsonl.gz file.
    """
    return dir_to_date(Path(path).parent)


def dir_to_date(dir):
    """
    Parse date when the scrapping has happened from given path
    to a directory of .jsonl.gz files.
    """
    dir = Path(dir)
    return date(year=int(dir.parent.parent.stem),
                month=int(dir.parent.stem),
                day=int(dir.stem))
