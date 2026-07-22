<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:import href="./core/pretext-latex.xsl"/>

<!-- Respect @workspace inside worksheet without requiring formatted="yes" -->
<xsl:template match="*" mode="sanitize-workspace">
    <xsl:apply-imports/>
</xsl:template>

<!-- Suppress the \newgeometry/\clearpage page break before worksheets -->
<xsl:template match="worksheet" mode="new-geometry"/>

<!-- Suppress the \restoregeometry/\clearpage page break after worksheets -->
<xsl:template match="worksheet" mode="latex-division-footing">
    <xsl:text>\end{</xsl:text>
    <xsl:apply-templates select="." mode="division-environment-name"/>
    <xsl:apply-templates select="." mode="division-environment-name-suffix"/>
    <xsl:text>}&#xa;</xsl:text>
</xsl:template>

</xsl:stylesheet>
