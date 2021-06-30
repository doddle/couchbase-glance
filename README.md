# Overview

This is just a quick and dirty CLI which speaks to your k8s cluster.

Its purpose is to quickly allow you to see how couchbase pods have landed in your k8s cluster.

# Usage

`make deps` will create a `venv/` folder with the deps declared in `requirements.txt`

`make run` will run the script




# what it does

- gathers zonal information about your k8s nodes and misc labels
- polls all pods on namespaces `couchbase` and `couchbase-sync`
- munges it all together in a simple table

# what we'd like it to do

- Actually do some health checks with the data
- are there unused couchbase nodes? (whats running on them otherwise)
- does it look like there is a misbalanced nodepool
- ensure data services are replicated into enough nodes / AZs
- allow configuration (alternative namespaces or labels)
