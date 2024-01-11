# helm-operator
Wrapper operator for helm chart

## Build

```bash
docker build -t <image_name>:<image_version> .  $(cat build.args | sed 's@^@--build-arg @g' | paste -s -d " ")
```
