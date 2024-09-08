FROM python:3.12

COPY . /app
RUN pip install -r /app/requirements.txt

WORKDIR /app
CMD ["python", "-m", "app"]
