FROM python:3-alpine

WORKDIR /root/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

COPY . .

CMD ["python", "main.py"]