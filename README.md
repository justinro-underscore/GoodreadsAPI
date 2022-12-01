# Goodreads API

Ever since Goodreads shut down their public API, there's been no way to get any information on our favorite books! After some digging, I've created this very inconsistent, pretty hacky solution for getting information from the Goodreads website. Using a mixture of public-facing APIs and web scraping, you can now get the information from any book on Goodreads!

## How to Use

In the future I may actually spin up a server that functions as an API but for now this serves more as a library. The main function is `get_book_info(query, author)` which returns a dictionary containing all the information pertaining to the book

**WARNING** I haven't put a lot of effort into this so it's still very finicky and inconsistent, and may take a couple of tries before any data is returned