ARG AIDO_REGISTRY
FROM ${AIDO_REGISTRY}/duckietown/aido-base-python3:daffy-aido4

ARG PIP_INDEX_URL
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

COPY requirements* ./
RUN pip install -r requirements.resolved
RUN pipdeptree

COPY . .

RUN PYTHON_PATH=. python3 -c "import scenario_maker"


ENTRYPOINT ["python3", "scenario_maker.py"]
