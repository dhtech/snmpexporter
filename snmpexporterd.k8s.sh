#!/bin/bash

kubectl create configmap snmpexporter --from-file etc/snmpexporter.yaml

kubectl apply -f snmpexporterd.k8s.yaml
