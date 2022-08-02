FROM python:3.10.6

WORKDIR /app

COPY setup.py .
COPY setup.cfg .

RUN	pip install -e .[dev,test,prod]

COPY . .

EXPOSE 2626

CMD ["./entrypoint.sh"]