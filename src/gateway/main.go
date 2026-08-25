// Intake gateway: the only synchronous hop before expensive OCR/embedding
// work. Rejects duplicate content (by SHA-256 hash) and malformed
// uploads cheaply, before a document reaches the extraction pipeline.
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/gin-gonic/gin"
)

const dedupTable = "geo-doc-dedup"
const docsBucket = "geo-docs"

type uploadRequest struct {
	ReportID string `json:"report_id" binding:"required"`
	Text     string `json:"text" binding:"required"`
}

func newAwsClients(ctx context.Context) (*dynamodb.Client, *s3.Client) {
	endpoint := os.Getenv("AWS_ENDPOINT_URL")
	if endpoint == "" {
		endpoint = "http://localhost:4566"
	}
	region := os.Getenv("AWS_REGION")
	if region == "" {
		region = "us-east-1"
	}
	cfg, err := config.LoadDefaultConfig(ctx,
		config.WithRegion(region),
		config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider("test", "test", "")),
	)
	if err != nil {
		log.Fatalf("failed to load AWS config: %v", err)
	}
	ddb := dynamodb.NewFromConfig(cfg, func(o *dynamodb.Options) { o.BaseEndpoint = aws.String(endpoint) })
	s3c := s3.NewFromConfig(cfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(endpoint)
		o.UsePathStyle = true
	})
	return ddb, s3c
}

func contentHash(text string) string {
	sum := sha256.Sum256([]byte(text))
	return hex.EncodeToString(sum[:])
}

func uploadHandler(ddb *dynamodb.Client, s3c *s3.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req uploadRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		if len(req.Text) < 20 {
			c.JSON(http.StatusBadRequest, gin.H{"error": "document text too short to be a real report"})
			return
		}

		hash := contentHash(req.Text)
		_, err := ddb.PutItem(c.Request.Context(), &dynamodb.PutItemInput{
			TableName: aws.String(dedupTable),
			Item: map[string]types.AttributeValue{
				"content_hash": &types.AttributeValueMemberS{Value: hash},
				"report_id":    &types.AttributeValueMemberS{Value: req.ReportID},
			},
			ConditionExpression: aws.String("attribute_not_exists(content_hash)"),
		})
		if err != nil {
			var condFailed *types.ConditionalCheckFailedException
			if errors.As(err, &condFailed) {
				c.JSON(http.StatusConflict, gin.H{"status": "duplicate", "content_hash": hash})
				return
			}
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		_, err = s3c.PutObject(c.Request.Context(), &s3.PutObjectInput{
			Bucket: aws.String(docsBucket),
			Key:    aws.String(req.ReportID + ".txt"),
			Body:   strings.NewReader(req.Text),
		})
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{"status": "accepted", "content_hash": hash})
	}
}

func healthHandler(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func main() {
	ctx := context.Background()
	ddb, s3c := newAwsClients(ctx)

	router := gin.Default()
	router.GET("/health", healthHandler)
	router.POST("/upload", uploadHandler(ddb, s3c))

	port := os.Getenv("GATEWAY_PORT")
	if port == "" {
		port = "8081"
	}
	log.Printf("intake gateway listening on :%s", port)
	if err := router.Run(":" + port); err != nil {
		log.Fatal(err)
	}
}
