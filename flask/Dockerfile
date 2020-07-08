FROM python:3.8-slim-buster

MAINTAINER Kristian Sloth Lauszus <lauszus@gmail.com>

# Get dependencies.
RUN DEBIAN_FRONTEND=noninteractive \
    apt-get -y update && \
    apt-get -y upgrade && \
    apt-get -y install --no-install-recommends build-essential python3-dev python3-pip libpcre3 libpcre3-dev && \
    apt-get clean

# Change the working directory to where our app will live.
WORKDIR /flask

# Copy over the requirements file, so we do not have to install all the dependencies again if any other file changes.
COPY requirements.txt .

# Install all requirements.
RUN pip3 install -U pip setuptools wheel && \
    pip3 install -r requirements.txt

# Copy over the app.
COPY . .

# Start the application on port 5000
EXPOSE 5000
CMD ["uwsgi", "--master", "--processes", "4", "--threads", "2", "--enable-threads", "--http-socket", "0.0.0.0:5000", "--http-timeout", "5", "-w", "wsgi:app"]
