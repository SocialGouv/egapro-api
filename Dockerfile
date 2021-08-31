FROM python:3.9.7

WORKDIR /app

COPY ./setup.py /app/setup.py
COPY ./setup.cfg /app/setup.cfg

RUN pip install /app[prod]

COPY ./egapro /app/egapro

EXPOSE 2626

CMD ["gunicorn", "egapro:app", "-b", ":2626", "--access-logfile=-", "--log-file=-", "--timeout", "600", "--reload", "--worker-class", "roll.worker.Worker"]
