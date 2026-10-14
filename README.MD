## setup kubernetes
```
cd external/cloud2023/kubernetes
```

#### before continuing, pull the latest
```
git submodule update --init --recursive
git submodule update --remote --merge
```

## install seluruh prerequisites
```
cd bin
sh download.sh
source set.sh
```

## install kubernetes cluster via kind
```
cd setup-cluster/kind
sh 1-create-cluster.sh
sh 2-set-config.sh
```


## install supporting metrics collector
```
cd setup-cluster/supporting
sh 3-install-ingress.sh
sh 4-cek-ingress.sh
sh 5-install-prometheus.sh
sh 6-install-linkerd.sh
sh 7-install-netobserv.sh
sh 8-install-inspektor-gadget.sh
sh 9-install-otel-collector.sh
```


