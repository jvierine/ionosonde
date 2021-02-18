find results/ -mtime 2 -name raw\*  |sed -e 's/.*/rm \0/'
