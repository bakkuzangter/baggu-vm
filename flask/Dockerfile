FROM python:3.9
RUN python -m pip install --upgrade pip
 
WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install -r requirements.txt

COPY . /app

CMD ["uwsgi", "uwsgi.ini"]
