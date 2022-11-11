
B=dts build_utils
B=dt-build_utils-cli


build:
	$(B) aido-container-build --use-branch daffy \
		--use-org duckietown-infrastructure \
		--push  --ignore-untagged --ignore-dirty  \
		--buildx --platforms linux/amd64,linux/arm64



bump: # v2
	bumpversion patch
	git push --tags
	git push





test1:
	python3 scenario_maker.py < test_data/in.json
