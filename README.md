# DL fork of [gcs-audit-log-smart-archive](https://github.com/domZippilli/gcs-audit-log-smart-archive)
Scripts to set up GCS audit logging and a smart archive cloud function.

Upstream docs are not great. Setup script is implented as a Makefile which walks through configuring a GCP project for dynamically pushing GCS storage objects into nearline storage using a cloud function running main.py

Presently (Sept 14 2019) we have only gone as far as to activating [activating the GCS audit logs](https://console.cloud.google.com/iam-admin/audit?project=dalhart-project-421) for reads and writes and adding a [log sink](https://console.cloud.google.com/logs/exports?project=dalhart-project-421) for these logs to get them into [this bigquery table](https://console.cloud.google.com/bigquery?project=dalhart-project-421&folder&organizationId&p=dalhart-project-421&d=gcs_access_logs).
