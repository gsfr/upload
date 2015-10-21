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
curl -X POST -F 'file=@data.bin' -F 'metadata={"foo": true}' http://localhost:8080/upload
```
