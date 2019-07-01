#!/usr/bin/env python3
from sys import exit
from google.cloud import bigquery
from google.cloud import storage
from google.api_core.exceptions import NotFound
from datetime import datetime, timezone

config = {
    "CONFIG_FILE_PATH": "./config.cfg"
}

def load_config():
    """
    Loads configuration file into module variables.
    """
    config_file = open(config["CONFIG_FILE_PATH"], "r")
    for line in config_file:
        k, v = line.split('=')
        config[k.strip()] = v.strip()
    for required in [
        'PROJECT',
        'DATASET_NAME',
        'DAYS_THRESHOLD',
            'NEW_STORAGE_CLASS']:
        if required not in config.keys() or config[required] is "CONFIGURE_ME":
            print('Missing required config item: {}'.format(required))
            sys.exit(1)


def initialize_moved_objects_table():
    """Creates, if not found, a table in which objects moved by this script to another storage class are stored. This table is used to exclude such items from future runs to keep execution time short.

    Returns:
        google.cloud.bigquery.table.RowIterator -- Result of the query. Since this is a DDL query, this will always be empty if it succeeded.

    Raises:
        google.cloud.exceptions.GoogleCloudError –- If the job failed.
        concurrent.futures.TimeoutError –- If the job did not complete in the given timeout.
    """
    bq = get_bq_client()

    moved_objects_table = "`{}.{}.objects_moved_to_{}`".format(
        config['PROJECT'], config['DATASET_NAME'], config['NEW_STORAGE_CLASS'])

    querytext = "CREATE TABLE IF NOT EXISTS {} (resourceName STRING)".format(
        moved_objects_table)

    query_job = bq.query(querytext)
    return query_job.result()


def query_access_table():
    """Queries the BigQuery audit log sink for the maximum access time of all objects which aren't in the moved objects table, and have been accessed since audit logging was turned on and sunk into the dataset.

    This is a wildcard table query, and can get quite large. To speed it up and lower costs, consider deleting tables older than the outer threshold for this script (e.g., 30 days, 60 days, 365 days, etc.)

    Returns:
        google.cloud.bigquery.table.RowIterator -- Result of the query. This will be all objects which haven't been moved and have been accessed since audit logging was turned on and sunk into this table.

    Raises:
        google.cloud.exceptions.GoogleCloudError – If the job failed.
        concurrent.futures.TimeoutError – If the job did not complete in the given timeout.
    """
    bq = get_bq_client()

    access_log_tables = "`{}.{}.cloudaudit_googleapis_com_data_access_*`".format(
        config['PROJECT'], config['DATASET_NAME'])

    moved_objects_table = "`{}.{}.objects_moved_to_{}`".format(
        config['PROJECT'], config['DATASET_NAME'], config['NEW_STORAGE_CLASS'])

    querytext = """
        SELECT
        a.protopayload_auditlog.resourceName  AS resourceName,
        MAX(a.timestamp)                      AS lastAccess
        FROM {0} as a
        LEFT JOIN {1} as b ON a.protopayload_auditlog.resourceName = b.resourceName
        WHERE b.resourceName IS NULL
        GROUP BY resourceName
    """.format(access_log_tables, moved_objects_table)
    query_job = bq.query(querytext)
    return query_job.result()


def insert_object_into_moved_objects(resource_name):
    """Insert the resource name of an object into the table of moved objects for exclusion later.

    Arguments:
        resource_name {str} -- The resource name of the object, as given in the audit log.

    Returns:
        google.cloud.bigquery.table.RowIterator -- Result of the query. Since this is an INSERT query, this will always be empty if it succeeded.

    Raises:
        google.cloud.exceptions.GoogleCloudError –- If the job failed.
        concurrent.futures.TimeoutError –- If the job did not complete in the given timeout.
    """
    bq = get_bq_client()

    moved_objects_table = "`{}.{}.objects_moved_to_{}`".format(
        config['PROJECT'], config['DATASET_NAME'], config['NEW_STORAGE_CLASS'])

    querytext = "INSERT INTO {} VALUES (\"{}\")".format(
        moved_objects_table, resource_name)

    query_job = bq.query(querytext)
    return query_job.result()


def evaluate_objects(audit_log):
    """Evaluates objects in the audit log to see if they should be moved to a new storage class.

    Arguments:
        audit_log {google.cloud.bigquery.table.RowIterator} -- The result set of a query of the audit log table, with the columns `resourceName` and `lastAccess`.
    """
    for row in audit_log:
        timedelta = datetime.now(tz=timezone.utc) - row.lastAccess
        bucket_name, object_name = get_bucket_and_path(row.resourceName)
        if timedelta.seconds > int(config['DAYS_THRESHOLD']):
            print("/".join(["gs:/",
                            bucket_name,
                            object_name]),
                  row.lastAccess,
                  "More than {} day(s) ago".format(config['DAYS_THRESHOLD']))
            gcs = get_gcs_client()
            bucket = storage.bucket.Bucket(gcs, name=bucket_name)
            try:
                blob = storage.blob.Blob(object_name, bucket)
                blob.update_storage_class(config['NEW_STORAGE_CLASS'])
                print("\tRewrote to: {}".format(config['NEW_STORAGE_CLASS']))
                insert_object_into_moved_objects(row.resourceName)
            except NotFound:
                print("Skipping, this object seems to have been deleted.")
        else:
            print("/".join(["gs:/",
                            bucket_name,
                            object_name]),
                  row.lastAccess,
                  "Less than {} day(s) ago".format(config['DAYS_THRESHOLD']))


def get_bucket_and_path(resource_name):
    """Given an audit log resourceName, parse out the bucket name and object path within the bucket.

    Returns:
        (str, str) -- ([bucket name], [object path])
    """
    pathparts = resource_name.split("buckets/", 1)[1].split("/", 1)
    return (pathparts[0], pathparts[1].split("objects/", 1)[1])


clients = {}


def get_bq_client():
    """Get a BigQuery client. Uses a simple create-if-not-found mechanism to avoid repeatedly creating new clients.

    Returns:
        google.cloud.bigquery.Client -- A BigQuery client.
    """
    if 'bq' not in clients:
        bq = bigquery.Client()
        clients['bq'] = bq
    return clients['bq']


def get_gcs_client():
    """Get a GCS client. Uses a simple create-if-not-found mechanism to avoid repeatedly creating new clients.

    Returns:
        google.cloud.storage.Client -- A GCS client.
    """
    if 'gcs' not in clients:
        gcs = storage.Client()
        clients['gcs'] = gcs
    return clients['gcs']


def archive_cold_objects(data, context):
    print("Loading config.")
    load_config()
    print("Initializing moved objects table (if not found).")
    initialize_moved_objects_table()
    print("Getting access log, except for already moved objects.")
    audit_log = query_access_table()
    print("Evaluating accessed objects for rewriting to {}.".format(config['NEW_STORAGE_CLASS']))
    evaluate_objects(audit_log)
    print("Done.")
    return "Done."


if __name__ == '__main__':
    archive_cold_objects(None, None)
