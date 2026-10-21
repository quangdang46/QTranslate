<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html"/>

  <xsl:template match="@* | node()">
    <xsl:copy>
      <xsl:apply-templates select="@* | node()"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="k">
    <div><b><xsl:value-of select="."/></b></div>
  </xsl:template>

  <xsl:template match="tr">
    <span>[<xsl:apply-templates/>]</span>
  </xsl:template>

  <xsl:template match="kref">
    <a href="qtdp:{.}"><xsl:value-of select="."/></a>
  </xsl:template>

  <xsl:template match="iref">
    <a href="{@href}"><xsl:value-of select="."/></a>
  </xsl:template>

  <xsl:template match="ex">
    <span style="color:gray"><xsl:apply-templates/></span>
  </xsl:template>
</xsl:stylesheet>
