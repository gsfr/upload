### Installation
```bash
virtualenv uploadenv
source uploadenv/bin/activate
pip install -r requirements.txt
```

### Usage
```bash
./upload.py -h
```

### Testing
```bash
curl -F 'file=@data.bin' -F 'metadata={"foo": true}' http://localhost:8080/upload | grep -v '^$'

curl -T data.bin http://localhost:8080/upload | grep -v '^$'
```
The ``` | grep -v '^$'``` enables ```curl```'s progress meter.
