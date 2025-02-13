FROM python:3.9-slim
LABEL maintainer "DataMade <info@datamade.us>"

RUN apt-get update && \
    apt-get install -y build-essential make git libpq-dev gcc libxml2-dev libxslt1-dev zlib1g-dev

RUN mkdir /app
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install pip==24.0 && pip install --no-cache-dir -r requirements.txt

COPY . /app
