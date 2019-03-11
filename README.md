## AWS S3 Glacier Restore
Utility script to restore files on AWS S3 that have GLACIER storage class.

### Features at a glance
- Calculates exact costs before restore
- Multithreaded API requests significantly reduce restore time
- Can check if all files for given prefix are already restored or not.  

### Installation and Upgrade
aws-s3-glacier-restore is developed in Python and uses [pip](http://www.pip-installer.org/en/latest/).<p>

The easiest way to install/upgrade s3select is to use `pip` in a `virtualenv`:

<pre>$ pip install -U aws-s3-glacier-restore</pre>

or, if you are not installing in a `virtualenv`, to install/upgrade globally:

<pre>$ sudo pip install -U aws-s3-glacier-restore</pre>

or for your user:

<pre>$ pip install --user -U aws-s3-glacier-restore</pre>

### Authentication

aws-s3-glacier-restore uses the same authentication and endpoint configuration as [aws-cli](https://github.com/aws/aws-cli#getting-started). If aws command is working on your machine, there is no need for any additional configuration.

### Example usage
First get some help:
<pre>
$ aws-s3-glacier-restore -h
usage: aws-s3-glacier-restore [-h] [-p PREFIX] [-i INPUT_FILE]
                              [-d DAYS_TO_KEEP] [-D DESTINATION_BUCKET]
                              [-t THREADS] [-s] [--profile PROFILE]

Utility script to restore files on AWS S3 that have GLACIER storage class

optional arguments:
  -h, --help            show this help message and exit
  -p PREFIX, --prefix PREFIX
                        S3 prefix URL to restore
  -i INPUT_FILE, --input_file INPUT_FILE
                        Input file containing all s3 paths to restore
  -d DAYS_TO_KEEP, --days_to_keep DAYS_TO_KEEP
                        How many days to keep restored files
  -D DESTINATION_BUCKET, --destination_bucket DESTINATION_BUCKET
                        Restore to this bucket instead of to original bucket
                        while preserving same path structure as in original
                        bucket. This is useful if you don't know for how long
                        you'll need restored files. Once you don't need them
                        you can delete them from destination bucket.
  -t THREADS, --threads THREADS
                        Number of threads to use. Default=40
  -s, --status_print    Just print status of files and how many of them are in
                        glacier and how many of them are restored already
  --profile PROFILE     Use a specific AWS profile from your credential file.
</pre>

Then full run might look like this:
<pre>
$ aws-s3-glacier-restore -p s3://test-restore-bucket/backup2/image_1503789115/part-r-0003 -d 2

Getting a listing of the files to restore... Done

About to restore 18.72GB in 10 files

Restore will cost us:
1) Expedited tier: $0.66
2) Standard tier:  $0.19
3) Bulk tier:      $0.05
Keeping files on S3 will cost: 0.02 per day
 
Press number in front of an option you wish or any other key to exit: 3
Starting restore using Bulk tier... Restoring backup2/image_1503789115/part-r-00030.gz
Restoring backup2/image_1503789115/part-r-00031.gz
Restoring backup2/image_1503789115/part-r-00032.gz
Restoring backup2/image_1503789115/part-r-00034.gz
Restoring backup2/image_1503789115/part-r-00036.gz
Restoring backup2/image_1503789115/part-r-00038.gz
Restoring backup2/image_1503789115/part-r-00033.gz
Restoring backup2/image_1503789115/part-r-00037.gz
Restoring backup2/image_1503789115/part-r-00035.gz
Restoring backup2/image_1503789115/part-r-00039.gz
Done
Time elapsed: 2s
</pre>

Parameter --days_to_keep (-d) specifies how long files will be accessible as regular files over S3. In case you have finished with files earlier than expected or want to extend the amount of days they are kept available, you can run the same command, but this time with modified "-d" parameter. If you specify "-d 1" this will signal that files should be archived back as soon as possible (usually happens within one day):
```
$ aws-s3-glacier-restore -p s3://test-restore-bucket/backup2/image_1503789115/part-r-0003 -d 0
```

If you want to check restore status of files you can use -s switch:
```
$ aws-s3-glacier-restore -p s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-0009 -s
Getting a listing of the files... Done

Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00091 is being restored
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00092 is in Glacier and not being restored
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00093 is in Glacier and not being restored
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00095 is in Glacier and not being restored
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00094 is in Glacier and not being restored
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00090 is restored until Fri, 19 Oct 2018 00:00:00 GMT
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00098 is restored until Fri, 19 Oct 2018 00:00:00 GMT
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00096 is restored until Mon, 24 Sep 2018 00:00:00 GMT
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00099 is in Glacier and not being restored
Object s3://test-restore-bucket/archives/cars/GlacierImageArchive_2017_10-00000001-r-00097 is in Glacier and not being restored
Restored count: 3/10
```
### License

Distributed under the MIT license. See `LICENSE` for more information.
