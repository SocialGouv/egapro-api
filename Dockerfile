FROM python:3.9.7

WORKDIR /app

COPY setup.py .
COPY setup.cfg .

RUN	pip install -e .[dev,test,prod]

COPY . .

EXPOSE 2626

CMD ["./entrypoint.sh"]