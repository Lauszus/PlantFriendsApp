FROM continuumio/miniconda3:latest

COPY requirements.txt requirements.txt

# Add conda-forge to get uwsgi
RUN conda config --add channels conda-forge && \
    conda create -y -n flask python=3 --file requirements.txt

# Copy over our app
COPY . /app

# Create a flask user to avoid running uwsgi as root
RUN useradd -r flask
RUN chown -R flask /app
USER flask

# activate the flask environment
ENV PATH /opt/conda/envs/flask/bin:$PATH

EXPOSE 5000

CMD ["uwsgi", "--enable-threads", "--http-socket", "0.0.0.0:5000", "-w", "wsgi:app"]
