## Streaming Video Identification

The identifier can identify HTTPS encrypted videos streamed using DASH, given a dataset of segment sizes. A demo of the running application can be seen [here](https://www.youtube.com/watch?v=8zF0GnYKhFc).

Our dataset contains videos from SVT Play and is automatically kept up-to-date, see https://github.com/embeage/dataset-updater.

## Getting Started

1. Begin by creating a Python virtual environment
   ```sh
   cd src
   python3 -m venv venv
   ```
2. Activate the virtual environment
    * On Windows
      ```sh
      venv\Scripts\activate.bat
      ``` 
    * On Unix or MacOS
      ```sh
      source venv/bin/activate
      ```
3. Install the project requirements inside the virtual environment
   ```sh
   python -m pip install -r requirements.txt
   ```

4. Download the SVT Play DB and place it inside `src/identifier`, select the international version if you are outside Sweden
   [svtplay_db.csv](https://drive.google.com/uc?id=1W9iS5sMaS5AkBCT4Zm5OWTZqegFcub57&export=download)
   [svtplay_db_intl.csv](https://drive.google.com/uc?id=1d5hUY0lUJeqv95mNzFkU8oloq1gMQFXu&export=download)

5. If you are on Linux you need to give tcpdump user level permissions. See https://askubuntu.com/a/632189 for Debian. Installing Wireshark is enough for Windows and Mac [https://www.wireshark.org/download.html](https://www.wireshark.org/download.html)

## Usage

### Running the identifier with the web interface

1. Start the Flask server from `src/identifier`
   ```sh
   flask run
   ```
2. Run the identifier and specify the network interface, e.g.
   ```sh
   python3 identifier.py -i en0
   ```

3. Go to [http://localhost:5000](http://localhost:5000) to see the output

### Running the identifier with terminal only

* Run the identifier, specify the network interface and specify the `--cli` option, e.g.
   ```sh
   python3 identifier.py -i en0 --cli
   ```

### Additional options

* If there is no output when streaming, try to run the application with the `--full-cdn-search` option
* Window width, K-d tree dimension and Pearson's r threshold can be set manually with the options `-w`, `-k` and `-p`
* Example:
   ```sh
   python3 identifier.py -i en0 -w 12 -k 6 -p 0.99 --cli --full-cdn-search
   ```
