<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:import href="./core/pretext-latex.xsl"/>

<!-- Respect @workspace inside worksheet (without requiring formatted="yes")
     and inside activity (PROJECT-LIKE). -->
<xsl:template match="*" mode="sanitize-workspace">
    <xsl:choose>
        <!-- activity case: same logic as pretext-common.xsl but for ancestor::activity -->
        <xsl:when test="ancestor::activity and not(child::task)">
            <xsl:variable name="raw-workspace">
                <xsl:choose>
                    <xsl:when test="self::task[@workspace]">
                        <xsl:value-of select="normalize-space(@workspace)"/>
                    </xsl:when>
                    <xsl:when test="self::task and ancestor::*[@workspace][1]">
                        <xsl:value-of select="normalize-space(ancestor::*[@workspace][1]/@workspace)"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="normalize-space(@workspace)"/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:variable>
            <xsl:choose>
                <xsl:when test="$raw-workspace = ''"/>
                <xsl:when test="substring($raw-workspace, string-length($raw-workspace) - 1) = 'in'">
                    <xsl:value-of select="$raw-workspace"/>
                </xsl:when>
                <xsl:when test="substring($raw-workspace, string-length($raw-workspace) - 1) = 'cm'">
                    <xsl:value-of select="$raw-workspace"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:text>2in</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:when>
        <!-- worksheet/handout case: delegate up the import chain -->
        <xsl:otherwise>
            <xsl:apply-imports/>
        </xsl:otherwise>
    </xsl:choose>
</xsl:template>

<!-- Use \vspace instead of \rule for workspace so that LaTeX discards the
     space automatically when it falls at the top of a new page, causing the
     next task to start at the top of that page rather than after blank space. -->
<xsl:template match="*" mode="workspace">
    <xsl:variable name="vertical-space">
        <xsl:apply-templates select="." mode="sanitize-workspace"/>
    </xsl:variable>
    <xsl:if test="not($vertical-space = '')">
        <xsl:text>\par\vspace{</xsl:text>
        <xsl:value-of select="$vertical-space"/>
        <xsl:text>}%&#xa;</xsl:text>
    </xsl:if>
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
