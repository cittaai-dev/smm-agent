"""step6_production_operations.md Part A §4 -- load testing to find real
concurrency limits (Postgres pool exhaustion, worker-generation queue
backup, ivfflat `lists` mismatch), not a correctness suite. Run against a
real staging deployment, never against a bare dev machine or CI's ephemeral
services container:

    locust -f tests/load/locustfile.py --headless -u 30 -r 5 --run-time 10m --host $STAGING_URL

Every endpoint here is read-only (health checks, GETs) -- this profiles read
load, not synthesis cost. A generative-path load test would burn real LLM
spend per request and belongs behind an explicit opt-in, not this default
file (dev_guidelines.md: don't build the general case before the concrete
need forces it -- add a separate `locustfile_generation.py` once a real
staging LLM budget exists for it).
"""

from locust import HttpUser, between, task


class OperatorUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health_live(self):
        self.client.get("/health/live")

    @task(3)
    def health_ready(self):
        self.client.get("/health/ready")

    @task(2)
    def data_source_health(self):
        self.client.get("/health/data-sources")

    @task(1)
    def metrics(self):
        self.client.get("/metrics")
