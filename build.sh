#!/bin/bash
rm -rf mortimer-build
mkdir mortimer-build
git rev-parse HEAD > resources/git-rev.txt
cp resources/git-rev.txt mortimer-build/git-rev.txt
lein uberjar
mv target/*-standalone.jar mortimer-build/mortimer.jar
#lein marg
mv docs/uberdoc.html mortimer-build/mortimer-doc.html
cp resources/public/vendor/swiss.css mortimer-build
cat > mortimer-build/README.html <<EOF
<html>
    <head><title>Mortimer</title></head>
    <link rel="stylesheet" type="text/css" href="swiss.css">
    <style>
    body {
        margin: 2em;
    }
    </style>
    <body>
EOF
echo '<div id="readme">' > resources/public/partials/README.html
curl https://api.github.com/markdown/raw -H'Content-Type: text/x-markdown' --data-binary @README.md >> resources/public/partials/README.html
echo '</div>' >> resources/public/partials/README.html
cat resources/public/partials/README.html >> mortimer-build/README.html
cat >> mortimer-build/README.html <<EOF
    </body>
</html>
EOF
