using CynclyDoraMetrics;

namespace CynclyDoraMetrics.Tests;

public class DoraMetricCalculatorTests
{
    [Fact]
    public void CalculateDeploymentFrequency_CountsUniqueDaysInReportingWindow()
    {
        var deploymentDates = new[]
        {
            new DateTime(2024, 8, 29, 9, 0, 0),
            new DateTime(2024, 8, 29, 15, 0, 0),
            new DateTime(2024, 8, 30, 8, 0, 0),
            new DateTime(2024, 9, 2, 7, 0, 0),
            new DateTime(2024, 9, 5, 10, 0, 0),
            new DateTime(2024, 9, 10, 9, 0, 0)
        };

        var result = DoraMetricCalculator.CalculateDeploymentFrequency(
            deploymentDates,
            new DateTime(2024, 8, 1),
            new DateTime(2024, 9, 30));

        Assert.Equal(5, result);
    }

    [Fact]
    public void CalculateMedianLeadTimeHours_ReturnsMedianAcrossValues()
    {
        var leadTimes = new[]
        {
            TimeSpan.FromHours(1),
            TimeSpan.FromHours(4),
            TimeSpan.FromHours(10),
            TimeSpan.FromHours(12),
            TimeSpan.FromHours(18)
        };

        var result = DoraMetricCalculator.CalculateMedianLeadTimeHours(leadTimes);

        Assert.Equal(10d, result, 3);
    }

    [Fact]
    public void CalculateMedianLeadTimeHours_ReturnsZero_WhenNoValuesAreProvided()
    {
        var result = DoraMetricCalculator.CalculateMedianLeadTimeHours(Array.Empty<TimeSpan>());

        Assert.Equal(0d, result);
    }

    [Fact]
    public void CalculateChangeFailureRate_Throws_WhenTotalDeploymentsIsZero()
    {
        var exception = Assert.Throws<ArgumentOutOfRangeException>(() =>
            DoraMetricCalculator.CalculateChangeFailureRate(0, 0));

        Assert.Equal("totalDeployments", exception.ParamName);
    }
}
