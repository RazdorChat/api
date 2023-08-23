FROM debian:bookworm
FROM python:bookworm

# Install the requirements
COPY requirements.txt pip_requirements.txt
RUN python3.11 -m pip install -r pip_requirements.txt
 



COPY ./ /src
WORKDIR /src

EXPOSE 3306
EXPOSE 6379

ENTRYPOINT ["python3.11", "api.py"]