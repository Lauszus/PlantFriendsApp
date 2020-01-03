FROM python:3.8-alpine

# Copy over our app
COPY . /flask
WORKDIR /flask

# Install dependencies for building the dependencies
RUN apk update && apk add gcc musl-dev linux-headers

# Install all requirements
RUN pip3 install -U pip setuptools wheel && \
    pip3 install -r requirements.txt

# Create a flask user to avoid running uwsgi as root
RUN adduser -S flask
RUN chown -R flask /flask
USER flask

# Start the application on port 5000
EXPOSE 5000
CMD ["uwsgi", "--enable-threads", "--http-socket", "0.0.0.0:5000", "--http-timeout", "5", "-w", "wsgi:app"]
