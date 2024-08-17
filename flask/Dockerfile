FROM python:3.9

# 최신 pip로 업그레이드
RUN python -m pip install --upgrade pip

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt를 먼저 복사하고 설치
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# 앱 소스 복사
COPY . /app

# Gunicorn을 사용해 Flask 앱 실행
CMD ["gunicorn", "-w", "4", "-k", "eventlet", "-b", "0.0.0.0:8000", "app:app"]
