Created openshift/mongodb.yaml. Deploy with:


oc apply -f openshift/mongodb.yaml
Once running, the MONGO_URI for the transcribe-api deployment would be:


mongodb://mongodb:27017
The Service name mongodb resolves within the same namespace. No credentials needed.


oc new-build --binary --strategy=docker --name=transcribe-api
oc start-build transcribe-api --from-dir=. --follow


oc new-build --binary --strategy=docker --name=shift-api
oc start-build shift-api --from-dir=. --follow
