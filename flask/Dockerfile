FROM python:3.8-buster

# Copy over our app
COPY . /app
WORKDIR /app

# Install all requirements
RUN pip3 install -U pip setuptools wheel && \
    pip3 install -r /app/requirements.txt

# Create a flask user to avoid running uwsgi as root
RUN useradd -r flask
RUN chown -R flask /app
USER flask

# Start the application on port 5000
EXPOSE 5000
CMD ["uwsgi", "--enable-threads", "--http-socket", "0.0.0.0:5000", "-w", "wsgi:app"]
