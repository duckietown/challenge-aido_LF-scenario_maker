
AIDO_REGISTRY ?= docker.io
PIP_INDEX_URL ?= https://pypi.org/simple

repo=challenge-aido_lf-scenario_maker
branch=$(shell git rev-parse --abbrev-ref HEAD)
tag=$(AIDO_REGISTRY)/duckietown/$(repo):$(branch)

update-reqs:
	pur --index-url $(PIP_INDEX_URL) -r requirements.txt -f -m '*' -o requirements.resolved
	aido-update-reqs requirements.resolved

build: update-reqs
	docker build --pull -t $(tag) --build-arg AIDO_REGISTRY=$(AIDO_REGISTRY) .

build-no-cache: update-reqs
	docker build --pull -t $(tag) --build-arg  AIDO_REGISTRY=$(AIDO_REGISTRY)  --no-cache .

push: build
	docker push $(tag)

test1:
	python3 scenario_maker.py < test_data/in.json
