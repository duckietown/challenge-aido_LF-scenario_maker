ARG DOCKER_REGISTRY
ARG ARCH=amd64
ARG MAJOR=daffy
ARG BASE_TAG=${MAJOR}


FROM ${DOCKER_REGISTRY}/duckietown/aido-base-python3:${BASE_TAG}

ARG PIP_INDEX_URL="https://pypi.org/simple"
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

COPY requirements.* ./
RUN cat requirements.* > .requirements.txt
RUN python3 -m pip install  -r .requirements.txt
RUN python3 -m pip list


RUN pipdeptree

COPY . .

RUN PYTHON_PATH=. python3 -c "import scenario_maker"


ENTRYPOINT ["python3", "scenario_maker.py"]
