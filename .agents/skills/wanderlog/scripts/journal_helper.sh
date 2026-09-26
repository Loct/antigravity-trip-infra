#!/usr/bin/env bash
# journal_helper.sh - Manage Wanderlog trip journal stops and upload/attach photos
set -euo pipefail

WANDERLOG_API_ORIGIN="${WANDERLOG_API_ORIGIN:-https://wanderlog.com}"

get_session_cookie() {
  if [[ -n "${WANDERLOG_AUTH_SESSION_COOKIE:-}" ]]; then
    echo "$WANDERLOG_AUTH_SESSION_COOKIE"
    return 0
  fi
  local creds_file="$HOME/.config/wanderlog/credentials.json"
  if [[ -f "$creds_file" ]]; then
    local cookie
    cookie=$(jq -r '.session // .SessionCookie // .session_cookie // empty' "$creds_file")
    if [[ -n "$cookie" ]]; then
      echo "$cookie"
      return 0
    fi
  fi
  echo "Error: No Wanderlog session cookie found in WANDERLOG_AUTH_SESSION_COOKIE or $creds_file" >&2
  exit 1
}

get_trip_json() {
  local trip_key="$1"
  local cookie
  cookie=$(get_session_cookie)
  curl -s "${WANDERLOG_API_ORIGIN}/api/tripPlans/${trip_key}?clientSchemaVersion=2" \
    -H "Cookie: connect.sid=${cookie}"
}

apply_ops() {
  local trip_key="$1"
  local ops_json="$2"
  local cookie
  cookie=$(get_session_cookie)

  local res
  res=$(curl -s -X POST "${WANDERLOG_API_ORIGIN}/api/tripPlans/${trip_key}/applyOps?clientSchemaVersion=2" \
    -H "Cookie: connect.sid=${cookie}" \
    -H "Content-Type: application/json" \
    -d "$ops_json")

  if echo "$res" | grep -q '"success":true'; then
    return 0
  else
    echo "Error applying ops: $res" >&2
    return 1
  fi
}

cmd_list() {
  local trip_key="$1"
  local trip_data
  trip_data=$(get_trip_json "$trip_key")

  local stops
  stops=$(echo "$trip_data" | jq '.tripPlan.itinerary.journal.stops // []')
  local count
  count=$(echo "$stops" | jq 'length')

  echo "📖 Journal Stops for Trip: ${trip_key} (${count} stops)"
  echo "---------------------------------------------------------"
  echo "$stops" | jq -r '
    to_entries[] | 
    "[\(.key)] ID: \(.value.id)\n    Title: \(.value.title)\n    Date: \(.value.dateTime // "None")\n    Place: \(.value.place.name // "None")\n    Media: \(.value.media | length) items"
  '
}

cmd_add_stop() {
  local trip_key="$1"
  shift

  local title=""
  local date_time=""
  local place_name=""
  local place_id=""
  local lat=""
  local lng=""
  local caption=""
  local insert_idx=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title) title="$2"; shift 2 ;;
      --date-time) date_time="$2"; shift 2 ;;
      --place-name) place_name="$2"; shift 2 ;;
      --place-id) place_id="$2"; shift 2 ;;
      --lat) lat="$2"; shift 2 ;;
      --lng) lng="$2"; shift 2 ;;
      --caption) caption="$2"; shift 2 ;;
      --index) insert_idx="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ -z "$title" ]]; then
    title="${place_name:-New Stop}"
  fi
  if [[ -z "$date_time" ]]; then
    date_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  fi

  # Generate 9-digit random stop ID
  local stop_id
  stop_id=$((100000000 + RANDOM % 900000000))

  local stop_obj
  stop_obj=$(perl -MJSON::PP -e '
    my ($id, $title, $dt, $p_name, $p_id, $lat, $lng, $caption) = @ARGV;
    my $stop = {
      id => int($id),
      type => "confirmed",
      title => $title,
      dateTime => $dt,
      endDateTime => undef,
      sourceStopId => undef,
      media => [],
      text => { ops => [{ insert => ($caption ? "$caption\n" : "\n") }] }
    };
    if ($p_name || $p_id || $lat) {
      $stop->{place} = {
        name => $p_name || $title,
        place_id => $p_id || undef,
        geometry => ($lat && $lng) ? { location => { lat => 0+$lat, lng => 0+$lng } } : undef
      };
    }
    print encode_json($stop);
  ' "$stop_id" "$title" "$date_time" "$place_name" "$place_id" "$lat" "$lng" "$caption")

  local payload
  payload=$(perl -MJSON::PP -e '
    my ($idx, $obj_json) = @ARGV;
    my $obj = decode_json($obj_json);
    my $payload = {
      ops => [
        {
          p => ["itinerary", "journal", "stops", int($idx)],
          li => $obj
        }
      ]
    };
    print encode_json($payload);
  ' "$insert_idx" "$stop_obj")

  echo "Adding journal stop '$title' at index $insert_idx (ID: $stop_id)..."
  apply_ops "$trip_key" "$payload"
  echo "✅ Successfully added journal stop (ID: $stop_id)!"
}

get_image_dimensions() {
  local file="$1"
  perl -e '
    use strict;
    my $file = $ARGV[0];
    open my $fh, "<:raw", $file or die "$!\n";
    read $fh, my $h, 2;
    if ($h eq "\xFF\xD8") { # JPEG
      while (read($fh, my $marker, 2)) {
        my ($ff, $type) = unpack("CC", $marker);
        last if $ff != 0xFF;
        read($fh, my $len_b, 2);
        my $len = unpack("n", $len_b);
        if ($type >= 0xC0 && $type <= 0xC3) {
          read($fh, my $sof, 5);
          my ($p, $h, $w) = unpack("Cnn", $sof);
          print "$w $h\n";
          exit 0;
        } else {
          read($fh, my $d, $len - 2);
        }
      }
    } elsif ($h eq "\x89P") { # PNG
      seek $fh, 16, 0;
      read $fh, my $wh, 8;
      my ($w, $h) = unpack("NN", $wh);
      print "$w $h\n";
      exit 0;
    }
    # fallback
    print "1024 1024\n";
  ' "$file"
}

cmd_attach_photo() {
  local trip_key="$1"
  local target_stop="$2"
  local photo_path="$3"

  if [[ ! -f "$photo_path" ]]; then
    echo "Error: File not found: $photo_path" >&2
    exit 1
  fi

  local cookie
  cookie=$(get_session_cookie)

  # Find stop index
  local trip_data
  trip_data=$(get_trip_json "$trip_key")
  local stop_idx=""
  if [[ "$target_stop" =~ ^[0-9]+$ ]] && [[ ${#target_stop} -le 3 ]]; then
    stop_idx="$target_stop"
  else
    # Find index by stop ID
    stop_idx=$(echo "$trip_data" | jq -r --arg id "$target_stop" '
      .tripPlan.itinerary.journal.stops // [] | 
      to_entries[] | select((.value.id | tostring) == $id) | .key
    ')
  fi

  if [[ -z "$stop_idx" || "$stop_idx" == "null" ]]; then
    echo "Error: Could not find journal stop '$target_stop'" >&2
    exit 1
  fi

  # Get dimensions
  read -r width height < <(get_image_dimensions "$photo_path")
  echo "Photo dimensions: ${width}x${height}"

  local mime="image/jpeg"
  if [[ "$photo_path" =~ \.png$ ]]; then
    mime="image/png"
  fi

  local metadata_json
  metadata_json=$(jq -n --arg mime "$mime" '{
    deviceId: "f28e962f-d7de-45d7-b451-2c5be097757e",
    mediaMetadata: [
      {
        localURL: "blob:https://wanderlog.com/photo-upload",
        mimeType: $mime,
        type: "image"
      }
    ]
  }')

  echo "Uploading photo to Wanderlog..."
  local upload_res
  upload_res=$(curl -s --max-time 60 \
    "${WANDERLOG_API_ORIGIN}/api/tripPlans/${trip_key}/media" \
    -H "Cookie: connect.sid=${cookie}" \
    -F "data=${metadata_json}" \
    -F "media0=@${photo_path};type=${mime};filename=$(basename "$photo_path")")

  local image_key
  image_key=$(echo "$upload_res" | jq -r '.data[0].key // empty')

  if [[ -z "$image_key" ]]; then
    echo "Error: Upload failed. Response: $upload_res" >&2
    exit 1
  fi

  echo "✅ Photo uploaded successfully! Image key: $image_key"

  # Find current media count on this stop
  local media_count
  media_count=$(echo "$trip_data" | jq -r --argjson idx "$stop_idx" '
    .tripPlan.itinerary.journal.stops[$idx].media // [] | length
  ')

  local media_obj
  media_obj=$(jq -n \
    --arg key "$image_key" \
    --argjson w "$width" \
    --argjson h "$height" \
    '{
      key: $key,
      width: $w,
      height: $h,
      mediaType: "image",
      type: "uploaded"
    }')

  local attach_payload
  attach_payload=$(jq -n \
    --argjson s_idx "$stop_idx" \
    --argjson m_idx "$media_count" \
    --argjson item "$media_obj" \
    '{
      ops: [
        {
          p: ["itinerary", "journal", "stops", $s_idx, "media", $m_idx],
          li: $item
        }
      ]
    }')

  echo "Attaching photo to stop at index $stop_idx..."
  apply_ops "$trip_key" "$attach_payload"
  echo "✅ Photo attached to journal stop $stop_idx successfully!"
  echo "CDN URL: https://itin-dev.wanderlogstatic.com/freeImage/$image_key"
}

cmd_edit_stop() {
  local trip_key="$1"
  local target_stop="$2"
  shift 2

  local title=""
  local date_time=""
  local caption=""
  local place_name=""
  local place_id=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title) title="$2"; shift 2 ;;
      --date-time) date_time="$2"; shift 2 ;;
      --caption) caption="$2"; shift 2 ;;
      --place-name) place_name="$2"; shift 2 ;;
      --place-id) place_id="$2"; shift 2 ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done

  # Find stop index
  local trip_data
  trip_data=$(get_trip_json "$trip_key")
  local stop_idx=""
  if [[ "$target_stop" =~ ^[0-9]+$ ]] && [[ ${#target_stop} -le 3 ]]; then
    stop_idx="$target_stop"
  else
    stop_idx=$(echo "$trip_data" | jq -r --arg id "$target_stop" '
      .tripPlan.itinerary.journal.stops // [] | 
      to_entries[] | select((.value.id | tostring) == $id) | .key
    ')
  fi

  if [[ -z "$stop_idx" || "$stop_idx" == "null" ]]; then
    echo "Error: Could not find journal stop '$target_stop'" >&2
    exit 1
  fi

  local ops="[]"
  if [[ -n "$title" ]]; then
    local old_title
    old_title=$(echo "$trip_data" | jq -r --argjson idx "$stop_idx" '.tripPlan.itinerary.journal.stops[$idx].title // ""')
    ops=$(echo "$ops" | jq --argjson idx "$stop_idx" --arg od "$old_title" --arg oi "$title" '
      . + [{ p: ["itinerary", "journal", "stops", $idx, "title"], od: $od, oi: $oi }]
    ')
  fi

  if [[ -n "$date_time" ]]; then
    local old_dt
    old_dt=$(echo "$trip_data" | jq -r --argjson idx "$stop_idx" '.tripPlan.itinerary.journal.stops[$idx].dateTime // ""')
    ops=$(echo "$ops" | jq --argjson idx "$stop_idx" --arg od "$old_dt" --arg oi "$date_time" '
      . + [{ p: ["itinerary", "journal", "stops", $idx, "dateTime"], od: $od, oi: $oi }]
    ')
  fi

  if [[ -n "$caption" ]]; then
    local old_text
    old_text=$(echo "$trip_data" | jq --argjson idx "$stop_idx" '.tripPlan.itinerary.journal.stops[$idx].text // {ops:[{insert:"\n"}]}')
    local new_text
    new_text=$(jq -n --arg cap "$caption" '{ ops: [{ insert: ($cap + "\n") }] }')
    ops=$(echo "$ops" | jq --argjson idx "$stop_idx" --argjson od "$old_text" --argjson oi "$new_text" '
      . + [{ p: ["itinerary", "journal", "stops", $idx, "text"], od: $od, oi: $oi }]
    ')
  fi

  if [[ -n "$place_name" || -n "$place_id" ]]; then
    local old_place
    old_place=$(echo "$trip_data" | jq --argjson idx "$stop_idx" '.tripPlan.itinerary.journal.stops[$idx].place // empty')
    local new_place
    new_place=$(echo "$old_place" | jq --arg name "${place_name:-}" --arg pid "${place_id:-}" '
      . + (if $name != "" then {name: $name} else {} end) + (if $pid != "" then {place_id: $pid} else {} end)
    ')
    ops=$(echo "$ops" | jq --argjson idx "$stop_idx" --argjson od "$old_place" --argjson oi "$new_place" '
      . + [{ p: ["itinerary", "journal", "stops", $idx, "place"], od: $od, oi: $oi }]
    ')
  fi

  local payload
  payload=$(jq -n --argjson ops "$ops" '{ ops: $ops }')

  echo "Updating stop at index $stop_idx..."
  apply_ops "$trip_key" "$payload"
  echo "✅ Journal stop updated successfully!"
}

usage() {
  cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  list <trip-key>
      List all journal stops for a trip.

  add-stop <trip-key> --title <title> --date-time <iso-timestamp> [options]
      Add a new journal stop.
      Options:
        --title <text>        Stop title
        --date-time <iso>     Date/time (e.g. 2026-09-26T17:00:00+02:00)
        --place-name <name>   Place name
        --place-id <id>       Google Place ID
        --lat <lat>           Latitude
        --lng <lng>           Longitude
        --caption <text>      Notes / caption
        --index <int>         Insertion index (default: 0)

  edit-stop <trip-key> <stop-id-or-index> [options]
      Edit an existing journal stop.
      Options:
        --title <text>        New title
        --date-time <iso>     New date/time
        --caption <text>      New caption / notes
        --place-name <name>   New place name
        --place-id <id>       New Google Place ID

  attach-photo <trip-key> <stop-id-or-index> <photo-path>
      Upload an image file and attach it to a journal stop.

EOF
}

case "${1:-}" in
  list)
    shift; cmd_list "$@" ;;
  add-stop)
    shift; cmd_add_stop "$@" ;;
  edit-stop)
    shift; cmd_edit_stop "$@" ;;
  attach-photo)
    shift; cmd_attach_photo "$@" ;;
  -h|--help|help)
    usage ;;
  *)
    usage; exit 1 ;;
esac
