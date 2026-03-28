Created openshift/mongodb.yaml. Deploy with:


oc apply -f openshift/mongodb.yaml
Once running, the MONGO_URI for the transcribe-api deployment would be:


oc create configmap run-config --from-file=config.yaml --dry-run=client -o yaml | oc apply -f -

oc set env deployment/llamastack-deployment \
  GRANITE_URL='https://granite32-8b.llama-serve.svc.cluster.local/v1' \
  GRANITE_MODEL='granite32-8b'

mongodb://mongodb:27017
The Service name mongodb resolves within the same namespace. No credentials needed.


oc new-build --binary --strategy=docker --name=atc-api
oc start-build atc-api --from-dir=.


oc new-build --binary --strategy=docker --name=web-ui \
  --build-arg VITE_API_URL=https://atc-api-llama-serve.apps.cluster-6k7wd.6k7wd.sandbox936.opentlc.com
oc start-build web-ui --from-dir=. 


