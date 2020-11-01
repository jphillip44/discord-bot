FROM python:latest

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ .

CMD [ "python", "-u", "bot/main.py" ]
