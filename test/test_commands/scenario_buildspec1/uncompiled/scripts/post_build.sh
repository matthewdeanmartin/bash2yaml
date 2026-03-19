echo "Running post-build steps..."
aws s3 sync dist/ s3://$BUCKET_NAME/
echo "Post-build complete."
