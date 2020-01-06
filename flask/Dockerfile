FROM python:3.8-alpine

MAINTAINER Kristian Sloth Lauszus <lauszus@gmail.com>

# Copy over our app
COPY . /flask
WORKDIR /flask

# Install dependencies for building the dependencies
RUN apk add --no-cache gcc musl-dev linux-headers pcre-dev

# Install all requirements
RUN pip3 install -U pip setuptools wheel && \
    pip3 install -r requirements.txt

# Start the application on port 5000
EXPOSE 5000
CMD ["uwsgi", "--master", "--processes", "4", "--threads", "2", "--enable-threads", "--http-socket", "0.0.0.0:5000", "--http-timeout", "5", "-w", "wsgi:app"]
