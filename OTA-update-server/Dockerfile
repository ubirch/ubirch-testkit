FROM python:3

WORKDIR /usr/src/app

RUN pip3 install --no-cache-dir pycryptodome

# This will copy the script and especially the firmware releases into the
# image. Make sure to create new images for each firmware release and
# tag them accordingly.
# The first line is to make sure there is at least one firmware release
# present to prevent someone from forgetting to add firmware before building
# the image.
COPY ./1.0.1/ ./1.0.1/ 
COPY . .

#we need the -u so the print statements are directly displayed and not buffered
CMD [ "python3", "-u" ,"./OTA_server.py" ]