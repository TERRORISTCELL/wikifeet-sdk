# WikiFeetSDK 🦶

An object-oriented, multi-language SDK for interacting with WikiFeet in **Python** and **PHP**. Supports celebrity search, galleries, photo tagging, comments, Guild chat, private messaging, and moderation tools.

---

## Features

- 🔍 **Instant Search:** Fast celebrity lookup with autocomplete details (`search`).
- 🖼️ **Galleries & Star Ratings:** Detailed 1–5 star breakdowns, favorites, ignore list, and alert subscriptions.
- 🏷️ **Fluent Tagging:** Chainable tag management (`photo.tags.soles(True).barefoot(True).commit()`).
- 📷 **Photo & Hand Photo Support:** High-res image URLs, uploader metadata, hand photo galleries, and image uploads.
- 💬 **Comments & Moderation:** Embedded comment threads, upvote/downvote (`Toe Up`/`Toe Down`), comment reporting, flagging, and moderation.
- 🏰 **Guild & Community Hub:** Join/leave Guilds, poll real-time chat, vote in council polls, and create announcements.
- 📩 **Private Messaging:** Inbox management, user threads, sending PMs, and blacklist management.
- 🛠️ **Utilities:** AI duplicate photo scanner, IMDb lookup, and account settings.

---

## Project Structure

```text
WikiFeetSDK/
├── python/                  # Python SDK
│   ├── WikiFeetClient.py
│   ├── models.py
│   └── exceptions.py
├── php/                     # PHP 8+ SDK
│   ├── autoload.php
│   ├── WikiFeetClient.php
│   ├── Models/
│   └── Exceptions/
└── README.md
```

---

## Python Usage

```python
from WikiFeetSDK import WikiFeetClient

# 1. Unauthenticated Guest Session
client = WikiFeetClient.as_guest()

# Search celebrities
results = client.search("Yurina")
print(results[0])  # {'cid': 1626096, 'name': 'Yurina Kumai', ...}

# Fetch celebrity gallery
gallery = client.gallery("Yurina_Hirate")
print(f"{gallery.cname} - Score: {gallery.score}")

# Iterate photos
for photo in gallery.photos:
    print(photo.pid, photo.image_url, photo.tags.list())

# 2. Authenticated User Session
user_client = WikiFeetClient.as_user("your_email@example.com", "your_password")
photo = gallery.photos[0]

# Fluent photo tagging
photo.tags.soles(True).barefoot(True).commit()

# Like & report photos
photo.like()
photo.report_no_feet()
```

---

## PHP Usage (PHP 8+)

```php
require_once __DIR__ . '/WikiFeetSDK/php/autoload.php';

use WikiFeetSDK\WikiFeetClient;

// 1. Unauthenticated Guest Session
$client = WikiFeetClient::asGuest();

// Search celebrities
$results = $client->search('Yurina');

// Fetch celebrity gallery
$gallery = $client->gallery('Yurina_Hirate');
echo "{$gallery->cname} - Score: {$gallery->score}\n";

// Fetch hand photos if available
if ($gallery->hasHands()) {
    $hands = $gallery->getHands();
    echo "Hand uploader: " . $hands[0]->getUploadedBy() . "\n";
}

// 2. Authenticated User Session
$userClient = WikiFeetClient::asUser('your_email@example.com', 'your_password');

// Rate celebrity & post comment
$gallery->rate(5);
$gallery->postComment("Stunning gallery!");
```

---

## License

MIT License.
