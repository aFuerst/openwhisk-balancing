FROM openwhisk/python3aiaction:nightly

RUN apt-get update
RUN apt-get install -y libsm6 libxext6 libxrender-dev coreutils
RUN python -m pip install chameleon
RUN python -m pip install pyaes

CMD ["/bin/bash", "-c", "cd /pythonAction && python -u pythonrunner.py"]