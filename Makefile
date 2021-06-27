

bump: # v2
	bumpversion patch
	git push --tags
	git push

build:
	dts build_utils aido-container-build --use-branch daffy --push





test1:
	python3 scenario_maker.py < test_data/in.json
