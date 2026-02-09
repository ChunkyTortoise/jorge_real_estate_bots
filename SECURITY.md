# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Email**: chunkytortoise@proton.me
2. **Subject**: `[SECURITY] jorge_real_estate_bots - Brief description`
3. **Do not** open a public GitHub issue for security vulnerabilities

We will acknowledge receipt within 48 hours and provide a detailed response within 7 days.

## Security Considerations

### PII Handling
This application processes personally identifiable information (PII) related to real estate transactions:

- **Contact information**: Names, emails, phone numbers from lead forms and CRM
- **Financial data**: Budget ranges, pre-approval amounts, income indicators
- **Property data**: Addresses, valuations, seller motivations

### Protections in Place

- **Environment variables**: All API keys (Anthropic, GoHighLevel, database credentials) are stored in environment variables, never hardcoded
- **JWT authentication**: API endpoints are protected with JWT tokens (1-hour expiry)
- **Rate limiting**: 100 requests/minute per client to prevent abuse
- **Input validation**: Pydantic models validate all API inputs
- **Database**: PostgreSQL with parameterized queries via SQLAlchemy (no raw SQL)
- **Redis**: Cache data has configurable TTL; no PII stored in cache by default
- **Demo mode**: Runs with synthetic data and no external API calls

### Compliance Context
- **DRE (Department of Real Estate)**: Bot conversations follow California DRE disclosure requirements
- **Fair Housing Act**: Bot prompts are designed to avoid protected class discrimination
- **CCPA**: Contact data can be exported and deleted upon request
- **CAN-SPAM**: Automated email sequences include unsubscribe mechanisms

## Dependencies

We monitor dependencies for known vulnerabilities. Report any concerns about third-party packages to the email above.
