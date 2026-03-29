from urllib.request import urlopen

h = urlopen("http://127.0.0.1:8000/marker/", timeout=5).read().decode("utf-8")
print("has debugLog id:", 'id="debugLog"' in h)
print("has markerUploadClick assign:", "window.markerUploadClick = onUploadClick" in h)
