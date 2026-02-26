# 新闻爬虫部署与本地运行 Makefile
# 部署前请设置: export GCP_PROJECT_ID=your-project-id
# 可选: export GCP_REGION=us-central1
# 本地运行默认用 uv；不用 uv 可覆盖: make run PYTHON=python

ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ROOT := $(patsubst %/,%,$(ROOT))
PYTHON ?= uv run python

.PHONY: help run run-browser install-browser deploy deploy-browser deploy-all

help:
	@echo "新闻爬虫 - 本地运行与部署"
	@echo ""
	@echo "用法: make <target> [PYTHON=python 覆盖默认 uv]"
	@echo ""
	@echo "本地运行（test 模式，不写 BigQuery）:"
	@echo "  run               简单爬虫 (techcrunch/apnews/coinlive)"
	@echo "  run-browser       无头浏览器爬虫 (stcn 等)，需先: make install-browser"
	@echo "  install-browser   安装浏览器依赖: requirements-browser.txt + playwright install firefox"
	@echo ""
	@echo "部署（需 GCP_PROJECT_ID）:"
	@echo "  deploy  部署简单爬虫到 Cloud Functions"
	@echo "  deploy-browser    部署无头浏览器爬虫到 Cloud Run + Cloud Scheduler"
	@echo "  deploy-all        依次执行 deploy 与 deploy-browser"
	@echo ""
	@echo "  help              本帮助（默认）"
	@echo ""
	@echo "示例:"
	@echo "  make run"
	@echo "  make run-browser"
	@echo "  make run PYTHON=python   # 不用 uv 时"
	@echo "  export GCP_PROJECT_ID=my-project && make deploy"

run:
	cd "$(ROOT)" && $(PYTHON) main.py

run-browser:
	cd "$(ROOT)" && $(PYTHON) main.py browser

install-browser:
	cd "$(ROOT)" && pip install -r requirements-browser.txt && $(PYTHON) -m playwright install firefox

deploy:
	@if [ -z "$$GCP_PROJECT_ID" ]; then echo "错误: 请设置 GCP_PROJECT_ID"; exit 1; fi
	cd "$(ROOT)" && sh deploy/deploy.sh

deploy-browser:
	@if [ -z "$$GCP_PROJECT_ID" ]; then echo "错误: 请设置 GCP_PROJECT_ID"; exit 1; fi
	cd "$(ROOT)" && sh deploy/deploy_cloudrun_browser.sh

deploy-all: deploy deploy-browser
