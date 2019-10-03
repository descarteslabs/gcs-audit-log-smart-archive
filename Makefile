NAME    = $(shell basename $(CURDIR))
VERSION = 0.0.2
PROJECT = automatapolis
KEYRING = automation-prod
KEY	    = k8s-secrets

IMAGE = us.gcr.io/${PROJECT}/${NAME}

TF_CMD  = cd deployment/terraform && terraform
TF_VARS = -var name=$(NAME) -var image=$(IMAGE):${VERSION} 

# change this as needed
.DEFAULT_GOAL		:= help

help:
	@echo "usage:"
	@echo "  make help          - print this message"
	@echo "  make info          - print name image and verion to stdout"
	@echo "  make build         - build dockerfile"
	@echo "  make push          - push image"
	@echo "  make tf_plan       - run terraform plan"
	@echo "  make tf_apply      - run terraform apply"
	@echo "  make deploy        - build, push and apply"
	@echo "  make tf_destroy    - terraform destroy"

info:
	@echo "$(NAME) $(VERSION) $(IMAGE):$(VERSION)" 

.PHONY: build
build:
	docker build \
		--file Dockerfile \
		-t $(IMAGE):$(VERSION) \
		--build-arg tag=${VERSION} \
		--cache-from $(IMAGE):latest \
		.
run:
	docker run $(IMAGE):$(VERSION)

push:
	docker push $(IMAGE):$(VERSION)
	docker tag $(IMAGE):$(VERSION) $(IMAGE):latest
	docker push $(IMAGE):latest
