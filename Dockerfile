FROM python:3.5-slim
LABEL maintainer "DataMade <info@datamade.us>"

RUN apt-get update && \
    apt-get install -y build-essential make git

RUN mkdir /app
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . /app
