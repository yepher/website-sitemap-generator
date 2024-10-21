RECENT_SITEMAP=$(find scrape/ -type f -name "sitemap.json" -print0 | xargs -0 ls -t | head -n 1)
if [ -n "$RECENT_SITEMAP" ]; then
    echo "Found sitemap.json: $RECENT_SITEMAP"
else
    echo "No sitemap.json found."
    exit 1
fi

jq 'to_entries as $pages               
    | reduce $pages[] as $entry ({};
        if $entry.value.http_status_code != 200 then
            .[$entry.key] = [
                $pages[]
                | select(.value.links | index($entry.key) != null)
                | .key
            ]
        else
            .
        end
    )' $RECENT_SITEMAP |tee output.json

