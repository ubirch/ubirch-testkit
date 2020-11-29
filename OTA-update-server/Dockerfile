FROM python:3

WORKDIR /usr/src/app

RUN pip3 install --no-cache-dir pycryptodome
 
COPY OTA_server.py .

# Copy  the firmware releases into the
# image. Make sure to create new images with each new
# firmware release and tag them accordingly.
COPY fw_releases ./fw_releases

#display contents for checking
RUN echo "\nIncluded firmware versions and files:\n" && ls -l ./fw_releases && echo " "

#we need the -u so the print statements are directly displayed and not buffered
CMD [ "python3", "-u" ,"./OTA_server.py" ]