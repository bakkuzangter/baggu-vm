FROM python:3.9

# 최신 pip로 업그레이드
RUN python -m pip install --upgrade pip

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    libdbus-1-dev \
    libgirepository1.0-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt를 먼저 복사하고 설치
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# 앱 소스 복사
COPY . /app

# static 폴더에 권한 설정 추가
RUN chmod -R 755 /app/static

EXPOSE 8000

# Gunicorn을 사용해 Flask 앱 실행
CMD ["gunicorn", "-w", "4", "-k", "eventlet", "-b", "0.0.0.0:8000", "app:app"]