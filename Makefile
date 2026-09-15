# Local development entrypoint.
# Every Kubernetes command runs against the repo-local kubeconfig (.kube/<cluster>.yaml) and
# an explicit context, so the host's default kube context is never used or modified.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

CLUSTER_NAME ?= retail-ontology
PIPELINE_IMAGE ?= retail-pipeline:dev
DATASET ?= dunnhumby-sample
KAGGLE_DATASET ?= frtgnn/dunnhumby-the-complete-journey

HOST_KUBECONFIG := $(or $(KUBECONFIG),$(HOME)/.kube/config)
export CLUSTER_NAME PIPELINE_IMAGE HOST_KUBECONFIG
export KUBECONFIG := $(CURDIR)/.kube/$(CLUSTER_NAME).yaml

PIPELINE_DIR := data-pipeline

##@ General

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target> [VAR=value]\n"} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)} \
		/^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: doctor
doctor: ## Check required tools, Docker resources, and kube context isolation
	@scripts/doctor.sh

##@ Lifecycle

.PHONY: up stop start down status
up: cluster-up infra-up lakehouse-bootstrap ## Create the cluster, deploy the platform, and bootstrap the lakehouse
stop: cluster-stop ## Stop the cluster and release CPU/memory (data is kept)
start: cluster-start ## Resume a stopped cluster
down: cluster-down ## Delete the cluster and all of its data
status: ## Show cluster, node, and pod status
	@scripts/cluster.sh status

##@ Cluster

.PHONY: cluster-up cluster-stop cluster-start cluster-down
cluster-up: ## Create or reuse the local k3d cluster
	@scripts/cluster.sh up
cluster-stop: ## Stop the k3d cluster
	@scripts/cluster.sh stop
cluster-start: ## Start the stopped k3d cluster
	@scripts/cluster.sh start
cluster-down: ## Delete the k3d cluster
	@scripts/cluster.sh down

##@ Platform

.PHONY: secrets infra-up infra-down lakehouse-bootstrap lakehouse-tables
secrets: ## Generate local credentials and sync them into Kubernetes Secrets
	@scripts/secrets.sh sync
infra-up: secrets ## Deploy PostgreSQL, SeaweedFS, Lakekeeper, and the pipeline runtime config
	@scripts/infra.sh up
infra-down: ## Remove the platform releases but keep the cluster
	@scripts/infra.sh down
lakehouse-bootstrap: pipeline-image ## Create buckets, bootstrap Lakekeeper, and create the warehouse and namespaces
	@scripts/pipeline-job.sh lakehouse-bootstrap -- lakehouse bootstrap
lakehouse-tables: pipeline-image ## List Iceberg tables with their record counts
	@scripts/pipeline-job.sh lakehouse-tables -- lakehouse tables

##@ Data pipeline

.PHONY: pipeline-sync pipeline-lint pipeline-format pipeline-test pipeline-image sample-data data-download ingest
pipeline-sync: ## Install data-pipeline dependencies with uv
	@cd $(PIPELINE_DIR) && uv sync
pipeline-lint: ## Check formatting and lint rules with ruff
	@cd $(PIPELINE_DIR) && uv run ruff format --check . && uv run ruff check .
pipeline-format: ## Apply ruff formatting and safe fixes
	@cd $(PIPELINE_DIR) && uv run ruff format . && uv run ruff check --fix .
pipeline-test: ## Run data-pipeline tests
	@cd $(PIPELINE_DIR) && uv run pytest
pipeline-image: ## Build the data-pipeline image and import it into the cluster
	@scripts/pipeline-image.sh
sample-data: ## Generate the dunnhumby-shaped sample dataset in data/raw/dunnhumby-sample
	@cd $(PIPELINE_DIR) && uv run retail-pipeline sample dunnhumby --output-dir "$(CURDIR)/data/raw/dunnhumby-sample"
data-download: ## Download the real dataset from Kaggle into data/raw/dunnhumby (needs your Kaggle API token)
	@scripts/data-download.sh "$(KAGGLE_DATASET)" "$(CURDIR)/data/raw/dunnhumby"
ingest: pipeline-image ## Land raw files and load Iceberg bronze tables (DATASET=dunnhumby-sample|dunnhumby)
	@scripts/pipeline-job.sh "ingest-$(DATASET)" -- ingest dunnhumby --input-dir "/mnt/host-data/raw/$(DATASET)"
