TEST_TARGETS:=test_pylint test_format

test: $(TEST_TARGETS)

test_pylint: nft_tool.py
	pylint $^

test_format: nft_tool.py
	isort --check $^
	black --check $^

format: nft_tool.py
	isort $^
	black $^

