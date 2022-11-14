

build:
	dt-build_utils-cli aido-container-build --use-branch daffy --ignore-dirty --ignore-untagged --push --buildx --platforms linux/amd64,linux/arm64



bump: # v2
	bumpversion patch
	git push --tags
	git push





test1:
	python3 scenario_maker.py < test_data/in.json
